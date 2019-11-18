import React, { Fragment } from 'react';
import PropTypes from 'prop-types';
import moment from 'moment';
import { Utils } from '../../utils/utils';
import { gettext, siteRoot, filePath, historyRepoID } from '../../utils/constants';
import URLDecorator from '../../utils/url-decorator';
import { Dropdown, DropdownToggle, DropdownMenu, DropdownItem } from 'reactstrap';

moment.locale(window.app.config.lang);

const propTypes = {
  item: PropTypes.object.isRequired,
  index: PropTypes.number.isRequired,
  canDownload: PropTypes.bool.isRequired,
  canCompare: PropTypes.bool.isRequired,
  onItemRestore: PropTypes.func.isRequired,
};

class HistoryItem extends React.Component {

  constructor(props) {
    super(props);
    this.state = {
      active: false,
    };
  }

  onMouseEnter = () => {
    this.setState({
      active: true
    });
  }

  onMouseLeave = () => {
    this.setState({
      active: false
    });
  }

  onItemRestore = (e) => {
    e.preventDefault();
    this.props.onItemRestore(this.props.item);
  }

  render() {
    let item = this.props.item;
    let downloadUrl = URLDecorator.getUrl({type: 'download_historic_file', filePath: filePath, objID: item.rev_file_id});
    let userProfileURL = `${siteRoot}profile/${encodeURIComponent(item.creator_email)}/`;
    let viewUrl = `${siteRoot}repo/${historyRepoID}/history/files/?obj_id=${item.rev_file_id}&commit_id=${item.commit_id}&p=${filePath}`;
    let diffUrl = `${siteRoot}repo/text_diff/${historyRepoID}/?commit=${item.commit_id}&p=${filePath}`;
    return (
      <Fragment>
        <tr onMouseEnter={this.onMouseEnter} onMouseLeave={this.onMouseLeave} className={this.state.active ? 'tr-highlight' : ''}>
          <td>
            <time datetime={item.time} is="relative-time" title={moment(item.ctime).format('llll')}>{moment(item.ctime).fromNow()}</time>
            {this.props.index === 0 && gettext('(current version)')}
          </td>
          <td>
            <img className="avatar" src={item.creator_avatar_url} alt=''></img>{' '}
            <a href={userProfileURL} target='_blank' className="username">{item.creator_name}</a>
          </td>
          <td>{Utils.bytesToSize(item.size)}</td>
          <td>
            {this.state.active &&
              <MoreMenu
                index={this.props.index}
                downloadUrl={downloadUrl}
                viewUrl={viewUrl}
                diffUrl={diffUrl}
                onItemRestore={this.onItemRestore}
                canDownload={this.props.canDownload}
                canCompare={this.props.canCompare}
              />
            }
          </td>
        </tr>
      </Fragment>
    );
  }
}

HistoryItem.propTypes = propTypes;


const MoreMenuPropTypes = {
  index: PropTypes.number.isRequired,
  downloadUrl: PropTypes.string.isRequired,
  viewUrl: PropTypes.string.isRequired,
  diffUrl: PropTypes.string.isRequired,
  onItemRestore: PropTypes.func.isRequired,
  canDownload: PropTypes.bool.isRequired,
  canCompare: PropTypes.bool.isRequired,
};

class MoreMenu extends React.PureComponent {

  constructor(props) {
    super(props);
    this.state = {
      dropdownOpen: false
    };
  }

  dropdownToggle = () => {
    this.setState({ dropdownOpen: !this.state.dropdownOpen });
  }

  render() {
    const { index, downloadUrl, viewUrl, diffUrl, onItemRestore, canCompare, canDownload } = this.props;
    return (
      <Dropdown isOpen={this.state.dropdownOpen} toggle={this.dropdownToggle} direction="down" className="mx-1 old-history-more-operation">
        <DropdownToggle
          tag='i'
          className='fa fa-ellipsis-v'
          title={gettext('More Operations')}
          data-toggle="dropdown" 
          aria-expanded={this.state.dropdownOpen}
        >
        </DropdownToggle>
        <DropdownMenu className="drop-list" right={true}>
          {index !== 0 && <a href="#" onClick={onItemRestore}><DropdownItem>{gettext('Restore')}</DropdownItem></a>}
          {canDownload && <a href={downloadUrl}><DropdownItem>{gettext('Download')}</DropdownItem></a>}
          <a href={viewUrl}><DropdownItem>{gettext('View')}</DropdownItem></a>
          {canCompare && <a href={diffUrl}><DropdownItem>{gettext('Diff')}</DropdownItem></a>}
        </DropdownMenu>
      </Dropdown>
    );
  }
}

MoreMenu.propTypes = MoreMenuPropTypes;

export default HistoryItem;
